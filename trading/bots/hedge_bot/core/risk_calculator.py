"""
NEXUS AI TRADING SYSTEM - Hedge Bot Risk Calculator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Calculateur de risque pour le bot de couverture
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
from scipy.stats import norm, t
from scipy.optimize import minimize_scalar
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class RiskMetric(Enum):
    """Métriques de risque"""
    VAR = "var"
    CVAR = "cvar"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    BETA = "beta"
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    STERLING = "sterling"
    ULCER = "ulcer"
    MARTIN = "martin"

class VarMethod(Enum):
    """Méthodes de calcul de VaR"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    EXTREME_VALUE = "extreme_value"

class DistributionType(Enum):
    """Types de distribution"""
    NORMAL = "normal"
    STUDENT = "student"
    SKEW_NORMAL = "skew_normal"
    GENERALIZED = "generalized"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class RiskInput:
    """Entrées de risque"""
    returns: List[float]
    confidence_level: float = 0.95
    time_horizon: int = 1  # days
    risk_free_rate: float = 0.02
    benchmark_returns: Optional[List[float]] = None
    method: VarMethod = VarMethod.HISTORICAL
    distribution: DistributionType = DistributionType.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskOutput:
    """Sorties de risque"""
    var: float
    cvar: float
    expected_shortfall: float
    volatility: float
    beta: Optional[float] = None
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    sterling_ratio: float = 0.0
    ulcer_index: float = 0.0
    martin_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    drawdown_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskConfig:
    """Configuration de risque"""
    default_confidence: float = 0.95
    default_time_horizon: int = 1
    var_method: VarMethod = VarMethod.HISTORICAL
    distribution: DistributionType = DistributionType.NORMAL
    risk_free_rate: float = 0.02
    max_drawdown_threshold: float = 0.15
    var_threshold: float = 0.05
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# RISK CALCULATOR
# ============================================================

class RiskCalculator:
    """
    Calculateur de risque pour le bot de couverture
    
    Implémente différentes métriques et méthodes de calcul de risque
    """
    
    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        update_interval: int = 3600,
        enable_monitoring: bool = True
    ):
        """
        Initialise le calculateur de risque
        
        Args:
            config: Configuration de risque
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or RiskConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Cache
        self._cache: Dict[str, RiskOutput] = {}
        self._cache_ttl: int = 300  # 5 minutes
        
        # Statistiques
        self.stats = {
            'total_calculations': 0,
            'avg_var': 0.0,
            'avg_cvar': 0.0,
            'avg_volatility': 0.0,
            'avg_sharpe': 0.0,
            'max_drawdown': 0.0,
            'total_risk_events': 0,
            'by_method': {},
        }
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        logger.info("RiskCalculator initialized")
    
    # ============================================================
    # RISK CALCULATION METHODS
    # ============================================================
    
    def calculate_risk(self, inputs: RiskInput) -> RiskOutput:
        """
        Calcule les métriques de risque
        
        Args:
            inputs: Entrées de risque
            
        Returns:
            RiskOutput: Sorties de risque
        """
        start_time = time.time()
        
        with self._lock:
            # Vérifier le cache
            cache_key = self._generate_cache_key(inputs)
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            returns = np.array(inputs.returns)
            if len(returns) == 0:
                return RiskOutput(0,0,0,0)
            
            # Calculer les métriques
            var = self._calculate_var(returns, inputs)
            cvar = self._calculate_cvar(returns, inputs)
            expected_shortfall = cvar
            volatility = np.std(returns)
            
            # Calculer les ratios
            sharpe_ratio = self._calculate_sharpe(returns, inputs)
            sortino_ratio = self._calculate_sortino(returns, inputs)
            
            # Drawdown
            max_drawdown, avg_drawdown, drawdown_duration = self._calculate_drawdown(returns)
            
            # Beta
            beta = self._calculate_beta(returns, inputs)
            
            # Ulcer Index
            ulcer_index = self._calculate_ulcer(returns)
            
            # Ratios
            calmar_ratio = self._calculate_calmar(returns, max_drawdown, inputs)
            sterling_ratio = self._calculate_sterling(returns, max_drawdown, inputs)
            martin_ratio = self._calculate_martin(returns, ulcer_index, inputs)
            
            output = RiskOutput(
                var=var,
                cvar=cvar,
                expected_shortfall=expected_shortfall,
                volatility=volatility,
                beta=beta,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                sterling_ratio=sterling_ratio,
                ulcer_index=ulcer_index,
                martin_ratio=martin_ratio,
                max_drawdown=max_drawdown,
                avg_drawdown=avg_drawdown,
                drawdown_duration=drawdown_duration,
                metadata={
                    'method': inputs.method.value,
                    'distribution': inputs.distribution.value,
                    'confidence_level': inputs.confidence_level,
                    'time_horizon': inputs.time_horizon,
                    'calculation_time': time.time() - start_time,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            # Mettre en cache
            self._cache[cache_key] = output
            
            # Mettre à jour les statistiques
            self._update_stats(output, inputs.method)
            
            return output
    
    def _calculate_var(self, returns: np.ndarray, inputs: RiskInput) -> float:
        """
        Calcule la Value at Risk (VaR)
        
        Args:
            returns: Rendements
            inputs: Entrées de risque
            
        Returns:
            float: VaR
        """
        method = inputs.method or self.config.var_method
        
        if method == VarMethod.HISTORICAL:
            return self._historical_var(returns, inputs.confidence_level)
        elif method == VarMethod.PARAMETRIC:
            return self._parametric_var(returns, inputs.confidence_level, inputs.distribution)
        elif method == VarMethod.MONTE_CARLO:
            return self._monte_carlo_var(returns, inputs.confidence_level)
        else:
            return self._historical_var(returns, inputs.confidence_level)
    
    def _historical_var(self, returns: np.ndarray, confidence: float) -> float:
        """
        VaR historique
        
        Args:
            returns: Rendements
            confidence: Niveau de confiance
            
        Returns:
            float: VaR
        """
        if len(returns) == 0:
            return 0.0
        
        sorted_returns = np.sort(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return -sorted_returns[index]
    
    def _parametric_var(self, returns: np.ndarray, confidence: float, distribution: DistributionType) -> float:
        """
        VaR paramétrique
        
        Args:
            returns: Rendements
            confidence: Niveau de confiance
            distribution: Type de distribution
            
        Returns:
            float: VaR
        """
        mean = np.mean(returns)
        std = np.std(returns)
        
        if distribution == DistributionType.NORMAL:
            z_score = norm.ppf(confidence)
            return -(mean + z_score * std)
        
        elif distribution == DistributionType.STUDENT:
            # Student-t distribution
            df = 4  # Degrés de liberté
            t_score = t.ppf(confidence, df)
            return -(mean + t_score * std * np.sqrt((df - 2) / df))
        
        else:
            return -(mean + norm.ppf(confidence) * std)
    
    def _monte_carlo_var(self, returns: np.ndarray, confidence: float, simulations: int = 10000) -> float:
        """
        VaR Monte Carlo
        
        Args:
            returns: Rendements
            confidence: Niveau de confiance
            simulations: Nombre de simulations
            
        Returns:
            float: VaR
        """
        mean = np.mean(returns)
        std = np.std(returns)
        
        # Simuler
        simulated_returns = np.random.normal(mean, std, simulations)
        sorted_returns = np.sort(simulated_returns)
        index = int((1 - confidence) * simulations)
        return -sorted_returns[index]
    
    def _calculate_cvar(self, returns: np.ndarray, inputs: RiskInput) -> float:
        """
        Calcule la Conditional Value at Risk (CVaR)
        
        Args:
            returns: Rendements
            inputs: Entrées de risque
            
        Returns:
            float: CVaR
        """
        var = self._calculate_var(returns, inputs)
        losses = returns[returns <= -var]
        
        if len(losses) == 0:
            return var
        
        return -np.mean(losses)
    
    def _calculate_sharpe(self, returns: np.ndarray, inputs: RiskInput) -> float:
        """
        Calcule le ratio de Sharpe
        
        Args:
            returns: Rendements
            inputs: Entrées de risque
            
        Returns:
            float: Ratio de Sharpe
        """
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        risk_free_rate = inputs.risk_free_rate or self.config.risk_free_rate
        annualized_return = mean_return * 252
        annualized_std = std_return * np.sqrt(252)
        
        return (annualized_return - risk_free_rate) / annualized_std if annualized_std > 0 else 0
    
    def _calculate_sortino(self, returns: np.ndarray, inputs: RiskInput) -> float:
        """
        Calcule le ratio de Sortino
        
        Args:
            returns: Rendements
            inputs: Entrées de risque
            
        Returns:
            float: Ratio de Sortino
        """
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        downside_deviation = np.std(downside_returns)
        
        if downside_deviation == 0:
            return 0.0
        
        risk_free_rate = inputs.risk_free_rate or self.config.risk_free_rate
        annualized_return = mean_return * 252
        annualized_downside = downside_deviation * np.sqrt(252)
        
        return (annualized_return - risk_free_rate) / annualized_downside if annualized_downside > 0 else 0
    
    def _calculate_drawdown(self, returns: np.ndarray) -> Tuple[float, float, float]:
        """
        Calcule les métriques de drawdown
        
        Args:
            returns: Rendements
            
        Returns:
            Tuple[float, float, float]: (max_drawdown, avg_drawdown, drawdown_duration)
        """
        if len(returns) == 0:
            return 0.0, 0.0, 0.0
        
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / running_max if any(running_max != 0) else 0
        
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        avg_drawdown = np.mean(drawdown) if len(drawdown) > 0 else 0
        
        # Durée du drawdown
        drawdown_duration = 0
        current_duration = 0
        
        for i, dd in enumerate(drawdown):
            if dd > 0:
                current_duration += 1
            else:
                if current_duration > drawdown_duration:
                    drawdown_duration = current_duration
                current_duration = 0
        
        return max_drawdown, avg_drawdown, drawdown_duration
    
    def _calculate_beta(self, returns: np.ndarray, inputs: RiskInput) -> Optional[float]:
        """
        Calcule le beta
        
        Args:
            returns: Rendements
            inputs: Entrées de risque
            
        Returns:
            Optional[float]: Beta
        """
        if inputs.benchmark_returns is None:
            return None
        
        benchmark_returns = np.array(inputs.benchmark_returns)
        if len(returns) != len(benchmark_returns):
            return None
        
        covariance = np.cov(returns, benchmark_returns)[0, 1]
        variance = np.var(benchmark_returns)
        
        if variance == 0:
            return 0.0
        
        return covariance / variance
    
    def _calculate_ulcer(self, returns: np.ndarray) -> float:
        """
        Calcule l'Ulcer Index
        
        Args:
            returns: Rendements
            
        Returns:
            float: Ulcer Index
        """
        if len(returns) == 0:
            return 0.0
        
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / running_max if any(running_max != 0) else 0
        
        return np.sqrt(np.mean(drawdown ** 2)) if len(drawdown) > 0 else 0
    
    def _calculate_calmar(self, returns: np.ndarray, max_drawdown: float, inputs: RiskInput) -> float:
        """
        Calcule le ratio de Calmar
        
        Args:
            returns: Rendements
            max_drawdown: Drawdown maximum
            inputs: Entrées de risque
            
        Returns:
            float: Ratio de Calmar
        """
        if max_drawdown == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        annualized_return = mean_return * 252
        
        return annualized_return / max_drawdown if max_drawdown > 0 else 0
    
    def _calculate_sterling(self, returns: np.ndarray, max_drawdown: float, inputs: RiskInput) -> float:
        """
        Calcule le ratio de Sterling
        
        Args:
            returns: Rendements
            max_drawdown: Drawdown maximum
            inputs: Entrées de risque
            
        Returns:
            float: Ratio de Sterling
        """
        if max_drawdown == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        annualized_return = mean_return * 252
        risk_free_rate = inputs.risk_free_rate or self.config.risk_free_rate
        
        return (annualized_return - risk_free_rate) / max_drawdown if max_drawdown > 0 else 0
    
    def _calculate_martin(self, returns: np.ndarray, ulcer_index: float, inputs: RiskInput) -> float:
        """
        Calcule le ratio de Martin
        
        Args:
            returns: Rendements
            ulcer_index: Ulcer Index
            inputs: Entrées de risque
            
        Returns:
            float: Ratio de Martin
        """
        if ulcer_index == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        annualized_return = mean_return * 252
        risk_free_rate = inputs.risk_free_rate or self.config.risk_free_rate
        
        return (annualized_return - risk_free_rate) / ulcer_index if ulcer_index > 0 else 0
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _generate_cache_key(self, inputs: RiskInput) -> str:
        """
        Génère une clé de cache
        
        Args:
            inputs: Entrées de risque
            
        Returns:
            str: Clé de cache
        """
        key = f"{inputs.method.value}_{inputs.distribution.value}_{inputs.confidence_level}_{len(inputs.returns)}"
        return key
    
    def _update_stats(self, output: RiskOutput, method: VarMethod):
        """
        Met à jour les statistiques
        
        Args:
            output: Sorties de risque
            method: Méthode de calcul
        """
        self.stats['total_calculations'] += 1
        
        method_key = method.value
        if method_key not in self.stats['by_method']:
            self.stats['by_method'][method_key] = 0
        self.stats['by_method'][method_key] += 1
        
        total = self.stats['total_calculations']
        self.stats['avg_var'] = (self.stats['avg_var'] * (total - 1) + output.var) / total
        self.stats['avg_cvar'] = (self.stats['avg_cvar'] * (total - 1) + output.cvar) / total
        self.stats['avg_volatility'] = (self.stats['avg_volatility'] * (total - 1) + output.volatility) / total
        self.stats['avg_sharpe'] = (self.stats['avg_sharpe'] * (total - 1) + output.sharpe_ratio) / total
        
        if output.max_drawdown > self.stats['max_drawdown']:
            self.stats['max_drawdown'] = output.max_drawdown
    
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
            'config': {
                'default_confidence': self.config.default_confidence,
                'var_method': self.config.var_method.value,
                'distribution': self.config.distribution.value,
                'risk_free_rate': self.config.risk_free_rate,
                'max_drawdown_threshold': self.config.max_drawdown_threshold,
                'var_threshold': self.config.var_threshold,
            }
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
        
        logger.info("RiskCalculator monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("RiskCalculator monitoring stopped")
    
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
        # Supprimer les entrées expirées
        now = time.time()
        for key in list(self._cache.keys()):
            if now - self._cache[key].metadata.get('timestamp', 0) > self._cache_ttl:
                del self._cache[key]

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_risk_calculator: Optional[RiskCalculator] = None

def get_risk_calculator(
    config: Optional[RiskConfig] = None
) -> RiskCalculator:
    """
    Récupère le calculateur de risque (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        RiskCalculator: Calculateur de risque
    """
    global _risk_calculator
    if _risk_calculator is None:
        _risk_calculator = RiskCalculator(config)
    return _risk_calculator

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'RiskMetric',
    'VarMethod',
    'DistributionType',
    'RiskInput',
    'RiskOutput',
    'RiskConfig',
    'RiskCalculator',
    'get_risk_calculator',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Risk calculator module initialized")
