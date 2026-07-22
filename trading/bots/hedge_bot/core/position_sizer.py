"""
NEXUS AI TRADING SYSTEM - Hedge Bot Position Sizer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Calculateur de taille de position pour le bot de couverture
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

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class PositionSizingMethod(Enum):
    """Méthodes de dimensionnement de position"""
    FIXED = "fixed"
    KELLY = "kelly"
    VOLATILITY = "volatility"
    RISK = "risk"
    ADAPTIVE = "adaptive"
    OPTIMAL = "optimal"
    MONTE_CARLO = "monte_carlo"
    CUSTOM = "custom"

class RiskMetric(Enum):
    """Métriques de risque"""
    VAR = "var"
    CVAR = "cvar"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    SHARPE = "sharpe"
    SORTINO = "sortino"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PositionSizingInput:
    """Entrées pour le dimensionnement de position"""
    capital: float
    risk_per_trade: float
    stop_loss_percent: float
    take_profit_percent: float
    volatility: float
    win_rate: float = 0.5
    avg_win: float = 1.0
    avg_loss: float = 1.0
    max_loss_per_day: float = 0.05
    max_loss_per_week: float = 0.10
    confidence_level: float = 0.95
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionSizingOutput:
    """Sorties du dimensionnement de position"""
    position_size: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    max_loss: float
    expected_value: float
    kelly_fraction: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionSizingConfig:
    """Configuration de dimensionnement de position"""
    method: PositionSizingMethod = PositionSizingMethod.RISK
    default_risk_per_trade: float = 0.01  # 1% of capital
    max_risk_per_trade: float = 0.02  # 2% of capital
    min_risk_per_trade: float = 0.005  # 0.5% of capital
    kelly_fraction: float = 0.25
    volatility_multiplier: float = 2.0
    max_position_size: float = 10000.0
    min_position_size: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# POSITION SIZER
# ============================================================

class PositionSizer:
    """
    Calculateur de taille de position pour le bot de couverture
    
    Implémente différentes méthodes de dimensionnement de position
    """
    
    def __init__(
        self,
        config: Optional[PositionSizingConfig] = None,
        update_interval: int = 60,
        enable_monitoring: bool = True
    ):
        """
        Initialise le calculateur de taille de position
        
        Args:
            config: Configuration
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or PositionSizingConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Statistiques
        self.stats = {
            'total_calculations': 0,
            'avg_position_size': 0.0,
            'max_position_size': 0.0,
            'min_position_size': 0.0,
            'by_method': {},
            'avg_risk': 0.0,
            'avg_reward': 0.0,
            'avg_risk_reward': 0.0,
        }
        
        # Cache
        self._cache: Dict[str, Any] = {}
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        logger.info("PositionSizer initialized")
    
    # ============================================================
    # POSITION SIZING METHODS
    # ============================================================
    
    def calculate_position_size(
        self,
        inputs: PositionSizingInput,
        method: Optional[PositionSizingMethod] = None
    ) -> PositionSizingOutput:
        """
        Calcule la taille de position
        
        Args:
            inputs: Entrées de dimensionnement
            method: Méthode de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        method = method or self.config.method
        start_time = time.time()
        
        with self._lock:
            # Vérifier le cache
            cache_key = self._generate_cache_key(inputs, method)
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            # Appliquer la méthode
            if method == PositionSizingMethod.FIXED:
                output = self._fixed_size(inputs)
            elif method == PositionSizingMethod.KELLY:
                output = self._kelly_size(inputs)
            elif method == PositionSizingMethod.VOLATILITY:
                output = self._volatility_size(inputs)
            elif method == PositionSizingMethod.RISK:
                output = self._risk_size(inputs)
            elif method == PositionSizingMethod.ADAPTIVE:
                output = self._adaptive_size(inputs)
            elif method == PositionSizingMethod.OPTIMAL:
                output = self._optimal_size(inputs)
            elif method == PositionSizingMethod.MONTE_CARLO:
                output = self._monte_carlo_size(inputs)
            else:
                output = self._risk_size(inputs)
            
            # Ajouter les métadonnées
            output.metadata['method'] = method.value
            output.metadata['calculation_time'] = time.time() - start_time
            output.metadata['timestamp'] = datetime.now().isoformat()
            
            # Mettre en cache
            self._cache[cache_key] = output
            
            # Mettre à jour les statistiques
            self._update_stats(output, method)
            
            return output
    
    def _fixed_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position fixe
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        position_size = self.config.default_risk_per_trade * inputs.capital
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=0.0,
            kelly_fraction=0.0
        )
    
    def _kelly_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position selon Kelly
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        # Calculer la fraction Kelly
        win_rate = inputs.win_rate
        avg_win = inputs.avg_win
        avg_loss = inputs.avg_loss
        
        if avg_loss == 0:
            kelly = 0
        else:
            kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)
            kelly = max(0, min(kelly, 1)) * self.config.kelly_fraction
        
        # Taille de position
        position_size = kelly * inputs.capital
        
        # Limiter la taille
        position_size = self._apply_limits(position_size)
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=(win_rate * avg_win) - ((1 - win_rate) * avg_loss),
            kelly_fraction=kelly
        )
    
    def _volatility_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position basée sur la volatilité
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        volatility = inputs.volatility
        risk_per_trade = self.config.default_risk_per_trade
        
        # Ajuster le risque en fonction de la volatilité
        adjusted_risk = risk_per_trade / (1 + volatility * self.config.volatility_multiplier)
        adjusted_risk = max(self.config.min_risk_per_trade, min(adjusted_risk, self.config.max_risk_per_trade))
        
        position_size = adjusted_risk * inputs.capital / inputs.stop_loss_percent
        
        # Limiter la taille
        position_size = self._apply_limits(position_size)
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=0.0,
            kelly_fraction=0.0
        )
    
    def _risk_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position basée sur le risque
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        risk_per_trade = inputs.risk_per_trade or self.config.default_risk_per_trade
        risk_per_trade = max(self.config.min_risk_per_trade, min(risk_per_trade, self.config.max_risk_per_trade))
        
        # Taille de position
        position_size = risk_per_trade * inputs.capital / inputs.stop_loss_percent
        
        # Limiter la taille
        position_size = self._apply_limits(position_size)
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=0.0,
            kelly_fraction=0.0
        )
    
    def _adaptive_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position adaptative
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        # Combinaison de différentes méthodes
        kelly_output = self._kelly_size(inputs)
        risk_output = self._risk_size(inputs)
        volatility_output = self._volatility_size(inputs)
        
        # Pondération adaptative
        weight_kelly = 0.3
        weight_risk = 0.4
        weight_volatility = 0.3
        
        position_size = (
            weight_kelly * kelly_output.position_size +
            weight_risk * risk_output.position_size +
            weight_volatility * volatility_output.position_size
        )
        
        # Limiter la taille
        position_size = self._apply_limits(position_size)
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=(weight_kelly * kelly_output.expected_value +
                          weight_risk * 0 +
                          weight_volatility * 0),
            kelly_fraction=kelly_output.kelly_fraction
        )
    
    def _optimal_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position optimale
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        # Optimisation basée sur l'espérance de gain
        win_rate = inputs.win_rate
        avg_win = inputs.avg_win
        avg_loss = inputs.avg_loss
        
        # Taille optimale
        if avg_loss > 0 and avg_win > 0:
            optimal_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / (avg_win * avg_loss)
            optimal_fraction = max(0, optimal_fraction)
        else:
            optimal_fraction = 0
        
        position_size = optimal_fraction * inputs.capital
        
        # Limiter la taille
        position_size = self._apply_limits(position_size)
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=(win_rate * avg_win) - ((1 - win_rate) * avg_loss),
            kelly_fraction=0.0
        )
    
    def _monte_carlo_size(self, inputs: PositionSizingInput) -> PositionSizingOutput:
        """
        Taille de position par Monte Carlo
        
        Args:
            inputs: Entrées de dimensionnement
            
        Returns:
            PositionSizingOutput: Résultat du dimensionnement
        """
        # Simuler différentes tailles de position
        best_size = 0
        best_sharpe = -float('inf')
        
        # Paramètres
        simulations = 1000
        risk_free_rate = 0.02
        
        for fraction in np.linspace(0.01, 0.5, 50):
            # Simuler les rendements
            returns = []
            for _ in range(simulations):
                # Simuler un trade
                if np.random.random() < inputs.win_rate:
                    pnl = fraction * inputs.capital * inputs.avg_win
                else:
                    pnl = -fraction * inputs.capital * inputs.avg_loss
                returns.append(pnl / inputs.capital)
            
            # Calculer le Sharpe ratio
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return - risk_free_rate) / std_return if std_return > 0 else 0
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_size = fraction * inputs.capital
        
        # Limiter la taille
        position_size = self._apply_limits(best_size)
        
        return PositionSizingOutput(
            position_size=position_size,
            risk_amount=position_size * inputs.stop_loss_percent,
            reward_amount=position_size * inputs.take_profit_percent,
            risk_reward_ratio=inputs.take_profit_percent / inputs.stop_loss_percent if inputs.stop_loss_percent > 0 else 0,
            max_loss=position_size * inputs.stop_loss_percent,
            expected_value=(inputs.win_rate * inputs.avg_win) - ((1 - inputs.win_rate) * inputs.avg_loss),
            kelly_fraction=0.0
        )
    
    def _apply_limits(self, position_size: float) -> float:
        """
        Applique les limites de taille
        
        Args:
            position_size: Taille de position
            
        Returns:
            float: Taille limitée
        """
        return max(self.config.min_position_size, min(position_size, self.config.max_position_size))
    
    # ============================================================
    # RISK METRICS
    # ============================================================
    
    def calculate_risk_metrics(
        self,
        positions: List[Dict[str, float]],
        metric: RiskMetric = RiskMetric.VAR
    ) -> Dict[str, float]:
        """
        Calcule les métriques de risque
        
        Args:
            positions: Liste des positions
            metric: Métrique de risque
            
        Returns:
            Dict[str, float]: Métriques de risque
        """
        if not positions:
            return {}
        
        # Extraire les P&L
        pnls = [p.get('pnl', 0) for p in positions]
        returns = [p.get('return', 0) for p in positions]
        
        if metric == RiskMetric.VAR:
            var_95 = np.percentile(pnls, 5)
            var_99 = np.percentile(pnls, 1)
            return {'var_95': var_95, 'var_99': var_99}
        
        elif metric == RiskMetric.CVAR:
            var_95 = np.percentile(pnls, 5)
            cvar_95 = np.mean([p for p in pnls if p <= var_95]) if len(pnls) > 0 else 0
            return {'cvar_95': cvar_95}
        
        elif metric == RiskMetric.DRAWDOWN:
            cumulative = np.cumsum(pnls)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (running_max - cumulative) / running_max if any(running_max != 0) else 0
            max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
            return {'max_drawdown': max_drawdown}
        
        elif metric == RiskMetric.VOLATILITY:
            volatility = np.std(returns) if len(returns) > 0 else 0
            return {'volatility': volatility}
        
        elif metric == RiskMetric.SHARPE:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return - 0.02) / std_return if std_return > 0 else 0
            return {'sharpe': sharpe}
        
        elif metric == RiskMetric.SORTINO:
            downside_returns = [r for r in returns if r < 0]
            mean_return = np.mean(returns)
            downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
            sortino = (mean_return - 0.02) / downside_deviation if downside_deviation > 0 else 0
            return {'sortino': sortino}
        
        return {}
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _generate_cache_key(
        self,
        inputs: PositionSizingInput,
        method: PositionSizingMethod
    ) -> str:
        """
        Génère une clé de cache
        
        Args:
            inputs: Entrées de dimensionnement
            method: Méthode de dimensionnement
            
        Returns:
            str: Clé de cache
        """
        key = f"{method.value}_{inputs.capital}_{inputs.risk_per_trade}_{inputs.stop_loss_percent}_{inputs.volatility}"
        return key
    
    def _update_stats(self, output: PositionSizingOutput, method: PositionSizingMethod):
        """
        Met à jour les statistiques
        
        Args:
            output: Résultat du dimensionnement
            method: Méthode de dimensionnement
        """
        self.stats['total_calculations'] += 1
        
        method_key = method.value
        if method_key not in self.stats['by_method']:
            self.stats['by_method'][method_key] = 0
        self.stats['by_method'][method_key] += 1
        
        # Mettre à jour les moyennes
        total = self.stats['total_calculations']
        self.stats['avg_position_size'] = (
            (self.stats['avg_position_size'] * (total - 1) + output.position_size) / total
        )
        self.stats['max_position_size'] = max(self.stats['max_position_size'], output.position_size)
        self.stats['min_position_size'] = min(self.stats['min_position_size'], output.position_size)
        self.stats['avg_risk'] = (
            (self.stats['avg_risk'] * (total - 1) + output.risk_amount) / total
        )
        self.stats['avg_reward'] = (
            (self.stats['avg_reward'] * (total - 1) + output.reward_amount) / total
        )
        self.stats['avg_risk_reward'] = (
            (self.stats['avg_risk_reward'] * (total - 1) + output.risk_reward_ratio) / total
        )
    
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
                'method': self.config.method.value,
                'default_risk_per_trade': self.config.default_risk_per_trade,
                'max_risk_per_trade': self.config.max_risk_per_trade,
                'min_risk_per_trade': self.config.min_risk_per_trade,
                'kelly_fraction': self.config.kelly_fraction,
                'max_position_size': self.config.max_position_size,
                'min_position_size': self.config.min_position_size,
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
        
        logger.info("PositionSizer monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("PositionSizer monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_metrics()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_metrics(self):
        """Met à jour les métriques"""
        # À implémenter avec les données réelles
        pass

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_position_sizer: Optional[PositionSizer] = None

def get_position_sizer(
    config: Optional[PositionSizingConfig] = None
) -> PositionSizer:
    """
    Récupère le calculateur de taille de position (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        PositionSizer: Calculateur de taille de position
    """
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer(config)
    return _position_sizer

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'PositionSizingMethod',
    'RiskMetric',
    'PositionSizingInput',
    'PositionSizingOutput',
    'PositionSizingConfig',
    'PositionSizer',
    'get_position_sizer',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Position sizer module initialized")
