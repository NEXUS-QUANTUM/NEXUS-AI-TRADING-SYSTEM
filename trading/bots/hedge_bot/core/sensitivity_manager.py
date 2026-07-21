"""
NEXUS AI TRADING SYSTEM - Hedge Bot Sensitivity Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de sensibilité pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class SensitivityType(Enum):
    """Types de sensibilité"""
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    LAMBDA = "lambda"
    EPSILON = "epsilon"
    ZETA = "zeta"
    ETA = "eta"
    IOTA = "iota"
    KAPPA = "kappa"
    MU = "mu"
    NU = "nu"
    XI = "xi"
    OMICRON = "omicron"
    PI = "pi"
    SIGMA = "sigma"
    TAU = "tau"
    UPSILON = "upsilon"
    PHI = "phi"
    CHI = "chi"
    PSI = "psi"
    OMEGA = "omega"

class SensitivityMethod(Enum):
    """Méthodes de calcul de sensibilité"""
    ANALYTICAL = "analytical"
    NUMERICAL = "numerical"
    MONTE_CARLO = "monte_carlo"
    FINITE_DIFFERENCE = "finite_difference"
    ADJOINT = "adjoint"
    AUTOMATIC = "automatic"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class SensitivityInput:
    """Entrées de sensibilité"""
    price: float
    strike: float
    volatility: float
    risk_free_rate: float
    time_to_expiry: float
    dividend_yield: float = 0.0
    option_type: str = "call"  # call / put
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SensitivityOutput:
    """Sorties de sensibilité"""
    delta: float
    gamma: float
    vega: float
    theta: float
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
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SensitivityPosition:
    """Position de sensibilité"""
    id: str
    symbol: str
    sensitivity_type: SensitivityType
    value: float
    exposure: float
    weight: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SensitivityMetrics:
    """Métriques de sensibilité"""
    total_delta: float
    total_gamma: float
    total_vega: float
    total_theta: float
    total_rho: float
    delta_exposure: float
    gamma_exposure: float
    vega_exposure: float
    theta_exposure: float
    rho_exposure: float
    convexity: float
    duration: float
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# SENSITIVITY MANAGER
# ============================================================

class SensitivityManager:
    """
    Gestionnaire de sensibilité pour le bot de couverture
    
    Calcule et gère les sensibilités des positions
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        update_interval: int = 60,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de sensibilité
        
        Args:
            config: Configuration
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or {}
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Positions de sensibilité
        self.positions: Dict[str, SensitivityPosition] = {}
        self.sensitivities: Dict[str, SensitivityOutput] = {}
        
        # Métriques
        self.metrics: Dict[str, SensitivityMetrics] = {}
        self.total_metrics: Optional[SensitivityMetrics] = None
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Statistiques
        self.stats = {
            'total_positions': 0,
            'by_type': {},
            'total_delta': 0.0,
            'total_gamma': 0.0,
            'total_vega': 0.0,
            'total_theta': 0.0,
            'total_rho': 0.0,
            'delta_exposure': 0.0,
            'gamma_exposure': 0.0,
            'vega_exposure': 0.0,
            'theta_exposure': 0.0,
            'rho_exposure': 0.0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("SensitivityManager initialized")
    
    # ============================================================
    # SENSITIVITY CALCULATION
    # ============================================================
    
    def calculate_sensitivity(self, inputs: SensitivityInput) -> SensitivityOutput:
        """
        Calcule les sensibilités Black-Scholes
        
        Args:
            inputs: Entrées de calcul
            
        Returns:
            SensitivityOutput: Sensibilités calculées
        """
        S = inputs.price
        K = inputs.strike
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        option_type = inputs.option_type
        
        if T <= 0:
            return SensitivityOutput(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
        
        # Calculs de base
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # Densité normale
        nd1 = norm.pdf(d1)
        nd2 = norm.pdf(d2)
        
        # Cumulative normale
        N_d1 = norm.cdf(d1)
        N_d2 = norm.cdf(d2)
        N_neg_d1 = norm.cdf(-d1)
        N_neg_d2 = norm.cdf(-d2)
        
        if option_type == "call":
            # Call sensitivities
            delta = math.exp(-q * T) * N_d1
            gamma = math.exp(-q * T) * nd1 / (S * sigma * math.sqrt(T))
            vega = S * math.exp(-q * T) * nd1 * math.sqrt(T)
            theta = -(S * sigma * math.exp(-q * T) * nd1) / (2 * math.sqrt(T)) - \
                    r * K * math.exp(-r * T) * N_d2 + \
                    q * S * math.exp(-q * T) * N_d1
            rho = K * T * math.exp(-r * T) * N_d2
        else:
            # Put sensitivities
            delta = -math.exp(-q * T) * N_neg_d1
            gamma = math.exp(-q * T) * nd1 / (S * sigma * math.sqrt(T))
            vega = S * math.exp(-q * T) * nd1 * math.sqrt(T)
            theta = -(S * sigma * math.exp(-q * T) * nd1) / (2 * math.sqrt(T)) + \
                    r * K * math.exp(-r * T) * N_neg_d2 - \
                    q * S * math.exp(-q * T) * N_neg_d1
            rho = -K * T * math.exp(-r * T) * N_neg_d2
        
        # Lambda (élasticité)
        lambda_val = delta * S / (S * math.exp(-q * T) * N_d1 if option_type == "call" else S * math.exp(-q * T) * N_neg_d1)
        
        # Epsilon (volatilité de la volatilité)
        epsilon = vega / S
        
        # Zeta (sensibilité au temps)
        zeta = theta / S
        
        # Eta (sensibilité au dividende)
        eta = -S * math.exp(-q * T) * T * N_d1 if option_type == "call" else -S * math.exp(-q * T) * T * N_neg_d1
        
        # Iota (sensibilité au strike)
        iota = -math.exp(-r * T) * N_d2 if option_type == "call" else math.exp(-r * T) * N_neg_d2
        
        # Kappa (sensibilité à la convexité)
        kappa = gamma * S ** 2 / 2
        
        # Mu (sensibilité au drift)
        mu = delta * S + gamma * S * sigma * math.sqrt(T) / 2
        
        # Nu (sensibilité à la skew)
        nu = -vega / (sigma * math.sqrt(T))
        
        # Xi (sensibilité à la courbe)
        xi = rho / S
        
        # Omicron (sensibilité à la liquidité)
        omicron = 1 / (S * (1 + gamma))
        
        # Pi (sensibilité au temps restant)
        pi = theta * T
        
        # Sigma (sensibilité à la volatilité implicite)
        sigma_val = vega
        
        # Tau (sensibilité au temps de maturité)
        tau = theta * T
        
        # Upsilon (sensibilité au taux de dividende)
        upsilon = eta
        
        # Phi (sensibilité à la corrélation)
        phi = 0.0  # À calculer
        
        # Chi (sensibilité au skew)
        chi = 0.0  # À calculer
        
        # Psi (sensibilité au smile)
        psi = 0.0  # À calculer
        
        # Omega (sensibilité à la courbe de taux)
        omega = rho
        
        return SensitivityOutput(
            delta=delta,
            gamma=gamma,
            vega=vega / 100,
            theta=theta / 365,
            rho=rho / 100,
            lambda_val=lambda_val,
            epsilon=epsilon,
            zeta=zeta,
            eta=eta,
            iota=iota,
            kappa=kappa,
            mu=mu,
            nu=nu,
            xi=xi,
            omicron=omicron,
            pi=pi,
            sigma=sigma_val,
            tau=tau,
            upsilon=upsilon,
            phi=phi,
            chi=chi,
            psi=psi,
            omega=omega
        )
    
    def calculate_sensitivity_numerical(
        self,
        inputs: SensitivityInput,
        epsilon: float = 0.01
    ) -> SensitivityOutput:
        """
        Calcule les sensibilités par méthode numérique
        
        Args:
            inputs: Entrées de calcul
            epsilon: Pas de différenciation
            
        Returns:
            SensitivityOutput: Sensibilités calculées
        """
        # Delta
        inputs_up = SensitivityInput(
            price=inputs.price * (1 + epsilon),
            strike=inputs.strike,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        inputs_down = SensitivityInput(
            price=inputs.price * (1 - epsilon),
            strike=inputs.strike,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        
        price_up = self._calculate_price(inputs_up)
        price_down = self._calculate_price(inputs_down)
        price_center = self._calculate_price(inputs)
        
        delta = (price_up - price_down) / (2 * inputs.price * epsilon)
        gamma = (price_up - 2 * price_center + price_down) / (inputs.price * epsilon) ** 2
        
        # Vega
        inputs_vol_up = SensitivityInput(
            price=inputs.price,
            strike=inputs.strike,
            volatility=inputs.volatility * (1 + epsilon),
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        inputs_vol_down = SensitivityInput(
            price=inputs.price,
            strike=inputs.strike,
            volatility=inputs.volatility * (1 - epsilon),
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        
        price_vol_up = self._calculate_price(inputs_vol_up)
        price_vol_down = self._calculate_price(inputs_vol_down)
        vega = (price_vol_up - price_vol_down) / (2 * inputs.volatility * epsilon * 100)
        
        # Theta
        inputs_time_up = SensitivityInput(
            price=inputs.price,
            strike=inputs.strike,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry + 1/365,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        inputs_time_down = SensitivityInput(
            price=inputs.price,
            strike=inputs.strike,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate,
            time_to_expiry=inputs.time_to_expiry - 1/365,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        
        price_time_up = self._calculate_price(inputs_time_up)
        price_time_down = self._calculate_price(inputs_time_down)
        theta = (price_time_down - price_time_up) / 2
        
        # Rho
        inputs_rate_up = SensitivityInput(
            price=inputs.price,
            strike=inputs.strike,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate * (1 + epsilon),
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        inputs_rate_down = SensitivityInput(
            price=inputs.price,
            strike=inputs.strike,
            volatility=inputs.volatility,
            risk_free_rate=inputs.risk_free_rate * (1 - epsilon),
            time_to_expiry=inputs.time_to_expiry,
            dividend_yield=inputs.dividend_yield,
            option_type=inputs.option_type
        )
        
        price_rate_up = self._calculate_price(inputs_rate_up)
        price_rate_down = self._calculate_price(inputs_rate_down)
        rho = (price_rate_up - price_rate_down) / (2 * inputs.risk_free_rate * epsilon * 100)
        
        return SensitivityOutput(
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta,
            rho=rho,
            lambda_val=0.0,
            epsilon=0.0,
            zeta=0.0,
            eta=0.0,
            iota=0.0,
            kappa=0.0,
            mu=0.0,
            nu=0.0,
            xi=0.0,
            omicron=0.0,
            pi=0.0,
            sigma=0.0,
            tau=0.0,
            upsilon=0.0,
            phi=0.0,
            chi=0.0,
            psi=0.0,
            omega=0.0
        )
    
    def _calculate_price(self, inputs: SensitivityInput) -> float:
        """
        Calcule le prix Black-Scholes
        
        Args:
            inputs: Entrées de calcul
            
        Returns:
            float: Prix calculé
        """
        S = inputs.price
        K = inputs.strike
        sigma = inputs.volatility
        r = inputs.risk_free_rate
        T = inputs.time_to_expiry
        q = inputs.dividend_yield
        option_type = inputs.option_type
        
        if T <= 0:
            return max(0, S - K) if option_type == "call" else max(0, K - S)
        
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        if option_type == "call":
            price = S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)
        
        return max(0, price)
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def add_position(self, position: SensitivityPosition):
        """
        Ajoute une position de sensibilité
        
        Args:
            position: Position à ajouter
        """
        with self._lock:
            self.positions[position.id] = position
            self.stats['total_positions'] += 1
            
            type_key = position.sensitivity_type.value
            self.stats['by_type'][type_key] = self.stats['by_type'].get(type_key, 0) + 1
            
            self._update_stats()
            logger.info(f"Sensitivity position added: {position.id}")
    
    def remove_position(self, position_id: str) -> bool:
        """
        Supprime une position de sensibilité
        
        Args:
            position_id: ID de la position
            
        Returns:
            bool: True si supprimée
        """
        with self._lock:
            if position_id not in self.positions:
                return False
            
            position = self.positions.pop(position_id)
            self.stats['total_positions'] -= 1
            
            type_key = position.sensitivity_type.value
            self.stats['by_type'][type_key] = self.stats['by_type'].get(type_key, 0) - 1
            
            self._update_stats()
            logger.info(f"Sensitivity position removed: {position_id}")
            return True
    
    def get_position(self, position_id: str) -> Optional[SensitivityPosition]:
        """
        Récupère une position de sensibilité
        
        Args:
            position_id: ID de la position
            
        Returns:
            Optional[SensitivityPosition]: Position
        """
        return self.positions.get(position_id)
    
    def get_positions_by_type(self, sensitivity_type: SensitivityType) -> List[SensitivityPosition]:
        """
        Récupère les positions par type
        
        Args:
            sensitivity_type: Type de sensibilité
            
        Returns:
            List[SensitivityPosition]: Positions
        """
        return [p for p in self.positions.values() if p.sensitivity_type == sensitivity_type]
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def calculate_metrics(self) -> SensitivityMetrics:
        """
        Calcule les métriques de sensibilité
        
        Returns:
            SensitivityMetrics: Métriques calculées
        """
        with self._lock:
            total_delta = 0.0
            total_gamma = 0.0
            total_vega = 0.0
            total_theta = 0.0
            total_rho = 0.0
            
            for position in self.positions.values():
                # Simuler les valeurs
                if position.sensitivity_type == SensitivityType.DELTA:
                    total_delta += position.value
                elif position.sensitivity_type == SensitivityType.GAMMA:
                    total_gamma += position.value
                elif position.sensitivity_type == SensitivityType.VEGA:
                    total_vega += position.value
                elif position.sensitivity_type == SensitivityType.THETA:
                    total_theta += position.value
                elif position.sensitivity_type == SensitivityType.RHO:
                    total_rho += position.value
            
            # Calculer les expositions
            delta_exposure = total_delta * 100
            gamma_exposure = total_gamma * 10000
            vega_exposure = total_vega * 100
            theta_exposure = abs(total_theta) * 100
            rho_exposure = abs(total_rho) * 100
            
            # Convexité et durée
            convexity = total_gamma / 2
            duration = total_theta / 365
            
            metrics = SensitivityMetrics(
                total_delta=total_delta,
                total_gamma=total_gamma,
                total_vega=total_vega,
                total_theta=total_theta,
                total_rho=total_rho,
                delta_exposure=delta_exposure,
                gamma_exposure=gamma_exposure,
                vega_exposure=vega_exposure,
                theta_exposure=theta_exposure,
                rho_exposure=rho_exposure,
                convexity=convexity,
                duration=duration
            )
            
            self.total_metrics = metrics
            return metrics
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        metrics = self.calculate_metrics()
        self.stats.update({
            'total_delta': metrics.total_delta,
            'total_gamma': metrics.total_gamma,
            'total_vega': metrics.total_vega,
            'total_theta': metrics.total_theta,
            'total_rho': metrics.total_rho,
            'delta_exposure': metrics.delta_exposure,
            'gamma_exposure': metrics.gamma_exposure,
            'vega_exposure': metrics.vega_exposure,
            'theta_exposure': metrics.theta_exposure,
            'rho_exposure': metrics.rho_exposure,
        })
    
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
        metrics = self.calculate_metrics()
        
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'metrics': {
                'total_delta': metrics.total_delta,
                'total_gamma': metrics.total_gamma,
                'total_vega': metrics.total_vega,
                'total_theta': metrics.total_theta,
                'total_rho': metrics.total_rho,
                'delta_exposure': metrics.delta_exposure,
                'gamma_exposure': metrics.gamma_exposure,
                'vega_exposure': metrics.vega_exposure,
                'theta_exposure': metrics.theta_exposure,
                'rho_exposure': metrics.rho_exposure,
                'convexity': metrics.convexity,
                'duration': metrics.duration,
            },
            'positions': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'type': p.sensitivity_type.value,
                    'value': p.value,
                    'exposure': p.exposure,
                    'weight': p.weight,
                }
                for p in self.positions.values()
            ],
            'history': self.history[-10:],
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
        
        logger.info("SensitivityManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("SensitivityManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_sensitivities()
                self._check_thresholds()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_sensitivities(self):
        """Met à jour les sensibilités"""
        # À implémenter avec les données réelles
        pass
    
    def _check_thresholds(self):
        """Vérifie les seuils de sensibilité"""
        metrics = self.calculate_metrics()
        
        # Vérifier les seuils
        thresholds = self.config.get('thresholds', {})
        if 'delta' in thresholds and abs(metrics.total_delta) > thresholds['delta']:
            self._add_alert(
                f"Delta threshold exceeded: {metrics.total_delta:.2f} > {thresholds['delta']:.2f}",
                "warning"
            )
        if 'gamma' in thresholds and abs(metrics.total_gamma) > thresholds['gamma']:
            self._add_alert(
                f"Gamma threshold exceeded: {metrics.total_gamma:.2f} > {thresholds['gamma']:.2f}",
                "warning"
            )
        if 'vega' in thresholds and abs(metrics.total_vega) > thresholds['vega']:
            self._add_alert(
                f"Vega threshold exceeded: {metrics.total_vega:.2f} > {thresholds['vega']:.2f}",
                "warning"
            )
        if 'theta' in thresholds and abs(metrics.total_theta) > thresholds['theta']:
            self._add_alert(
                f"Theta threshold exceeded: {metrics.total_theta:.2f} > {thresholds['theta']:.2f}",
                "warning"
            )
        if 'rho' in thresholds and abs(metrics.total_rho) > thresholds['rho']:
            self._add_alert(
                f"Rho threshold exceeded: {metrics.total_rho:.2f} > {thresholds['rho']:.2f}",
                "warning"
            )
    
    def _add_alert(self, message: str, severity: str = "info"):
        """
        Ajoute une alerte
        
        Args:
            message: Message
            severity: Sévérité
        """
        alert = {
            'timestamp': time.time(),
            'severity': severity,
            'message': message,
        }
        self.alerts.append(alert)
        
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_sensitivity_manager: Optional[SensitivityManager] = None

def get_sensitivity_manager(
    config: Optional[Dict[str, Any]] = None
) -> SensitivityManager:
    """
    Récupère le gestionnaire de sensibilité (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        SensitivityManager: Gestionnaire de sensibilité
    """
    global _sensitivity_manager
    if _sensitivity_manager is None:
        _sensitivity_manager = SensitivityManager(config)
    return _sensitivity_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'SensitivityType',
    'SensitivityMethod',
    'SensitivityInput',
    'SensitivityOutput',
    'SensitivityPosition',
    'SensitivityMetrics',
    'SensitivityManager',
    'get_sensitivity_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Sensitivity manager module initialized")
