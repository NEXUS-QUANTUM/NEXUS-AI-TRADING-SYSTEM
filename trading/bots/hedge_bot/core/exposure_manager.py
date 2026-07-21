"""
NEXUS AI TRADING SYSTEM - Hedge Bot Exposure Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire d'exposition pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import numpy as np

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class ExposureType(Enum):
    """Types d'exposition"""
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    BETA = "beta"
    CURRENCY = "currency"
    COUNTERPARTY = "counterparty"
    LIQUIDITY = "liquidity"
    CONCENTRATION = "concentration"
    CORRELATION = "correlation"

class ExposureDirection(Enum):
    """Directions d'exposition"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"

class HedgingStrategy(Enum):
    """Stratégies de couverture"""
    DELTA_HEDGE = "delta_hedge"
    GAMMA_HEDGE = "gamma_hedge"
    VEGA_HEDGE = "vega_hedge"
    BETA_HEDGE = "beta_hedge"
    CURRENCY_HEDGE = "currency_hedge"
    PORTFOLIO_HEDGE = "portfolio_hedge"
    DYNAMIC_HEDGE = "dynamic_hedge"
    STATIC_HEDGE = "static_hedge"
    OPTIMAL_HEDGE = "optimal_hedge"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Exposure:
    """Exposition"""
    type: ExposureType
    direction: ExposureDirection
    value: float
    asset: str
    currency: str = "USD"
    percentage: float = 0.0
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    rho: Optional[float] = None
    beta: Optional[float] = None
    correlation: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class ExposureLimit:
    """Limite d'exposition"""
    type: ExposureType
    asset: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_percentage: Optional[float] = None
    max_percentage: Optional[float] = None
    severity: str = "warning"
    action: str = "notify"

@dataclass
class HedgingPosition:
    """Position de couverture"""
    id: str
    asset: str
    size: float
    price: float
    delta: float
    gamma: float
    vega: float
    strategy: HedgingStrategy
    entry_time: float
    expiry: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# EXPOSURE MANAGER
# ============================================================

class ExposureManager:
    """
    Gestionnaire d'exposition pour le bot de couverture
    
    Gère, surveille et couvre les expositions du portefeuille
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        update_interval: int = 60,
        enable_auto_hedging: bool = True
    ):
        """
        Initialise le gestionnaire d'exposition
        
        Args:
            config: Configuration
            update_interval: Intervalle de mise à jour
            enable_auto_hedging: Activer la couverture automatique
        """
        self.config = config or {}
        self.update_interval = update_interval
        self.enable_auto_hedging = enable_auto_hedging
        
        # Exposition
        self.exposures: Dict[str, List[Exposure]] = defaultdict(list)
        self.total_exposure: Dict[str, float] = {}
        self.exposure_limits: List[ExposureLimit] = []
        self.exposure_breakdown: Dict[str, Any] = {}
        
        # Couverture
        self.hedging_positions: Dict[str, HedgingPosition] = {}
        self.hedge_ratios: Dict[str, float] = {}
        self.hedge_effectiveness: Dict[str, float] = {}
        
        # Statistiques
        self.stats = {
            'total_exposure': 0.0,
            'hedged_exposure': 0.0,
            'unhedged_exposure': 0.0,
            'hedge_ratio': 0.0,
            'exposure_by_type': {},
            'exposure_by_asset': {},
            'exposure_by_currency': {},
            'hedging_positions': 0,
            'hedge_effectiveness': 0.0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Charger les limites
        self._load_limits()
        
        # Démarrer la mise à jour
        if update_interval > 0:
            self.start()
        
        logger.info("ExposureManager initialized")
    
    def _load_limits(self):
        """Charge les limites d'exposition"""
        default_limits = [
            ExposureLimit(
                type=ExposureType.DELTA,
                asset='BTC/USDT',
                max_percentage=0.30,
                severity='warning'
            ),
            ExposureLimit(
                type=ExposureType.DELTA,
                asset='ETH/USDT',
                max_percentage=0.25,
                severity='warning'
            ),
            ExposureLimit(
                type=ExposureType.CONCENTRATION,
                asset='*',
                max_percentage=0.40,
                severity='critical'
            ),
        ]
        
        self.exposure_limits = default_limits
    
    # ============================================================
    # EXPOSURE MANAGEMENT
    # ============================================================
    
    def add_exposure(self, exposure: Exposure):
        """
        Ajoute une exposition
        
        Args:
            exposure: Exposition à ajouter
        """
        with self._lock:
            key = f"{exposure.type.value}_{exposure.asset}"
            self.exposures[key].append(exposure)
            
            # Limiter l'historique
            if len(self.exposures[key]) > 100:
                self.exposures[key] = self.exposures[key][-100:]
            
            # Mettre à jour les statistiques
            self._update_stats()
            
            # Vérifier les limites
            self._check_limits()
    
    def remove_exposure(self, exposure_id: str):
        """
        Supprime une exposition
        
        Args:
            exposure_id: ID de l'exposition
        """
        with self._lock:
            for key, exposures in self.exposures.items():
                self.exposures[key] = [e for e in exposures if e.metadata.get('id') != exposure_id]
            
            self._update_stats()
    
    def get_exposures(
        self,
        asset: Optional[str] = None,
        type: Optional[ExposureType] = None
    ) -> List[Exposure]:
        """
        Récupère les expositions
        
        Args:
            asset: Actif
            type: Type d'exposition
            
        Returns:
            List[Exposure]: Expositions
        """
        with self._lock:
            results = []
            
            for key, exposures in self.exposures.items():
                for exposure in exposures:
                    if asset and exposure.asset != asset:
                        continue
                    if type and exposure.type != type:
                        continue
                    results.append(exposure)
            
            return results
    
    def get_total_exposure(
        self,
        asset: Optional[str] = None,
        type: Optional[ExposureType] = None
    ) -> float:
        """
        Récupère l'exposition totale
        
        Args:
            asset: Actif
            type: Type d'exposition
            
        Returns:
            float: Exposition totale
        """
        exposures = self.get_exposures(asset, type)
        return sum(e.value for e in exposures)
    
    def get_exposure_by_type(self) -> Dict[str, float]:
        """
        Récupère l'exposition par type
        
        Returns:
            Dict[str, float]: Exposition par type
        """
        with self._lock:
            result = {}
            for key, exposures in self.exposures.items():
                type_name = key.split('_')[0]
                result[type_name] = sum(e.value for e in exposures)
            return result
    
    def get_exposure_by_asset(self) -> Dict[str, float]:
        """
        Récupère l'exposition par actif
        
        Returns:
            Dict[str, float]: Exposition par actif
        """
        with self._lock:
            result = {}
            for key, exposures in self.exposures.items():
                asset = key.split('_')[1] if '_' in key else 'unknown'
                result[asset] = sum(e.value for e in exposures)
            return result
    
    def get_exposure_breakdown(self) -> Dict[str, Any]:
        """
        Récupère la répartition de l'exposition
        
        Returns:
            Dict[str, Any]: Répartition de l'exposition
        """
        with self._lock:
            return {
                'by_type': self.get_exposure_by_type(),
                'by_asset': self.get_exposure_by_asset(),
                'total': sum(self.get_exposure_by_type().values()),
            }
    
    # ============================================================
    # LIMITS MANAGEMENT
    # ============================================================
    
    def add_limit(self, limit: ExposureLimit):
        """
        Ajoute une limite d'exposition
        
        Args:
            limit: Limite d'exposition
        """
        self.exposure_limits.append(limit)
        logger.info(f"Exposure limit added: {limit.type.value} for {limit.asset}")
    
    def remove_limit(self, limit_id: str):
        """
        Supprime une limite d'exposition
        
        Args:
            limit_id: ID de la limite
        """
        self.exposure_limits = [l for l in self.exposure_limits if l.metadata.get('id') != limit_id]
    
    def _check_limits(self):
        """Vérifie les limites d'exposition"""
        exposures = self.get_exposures()
        total_value = sum(e.value for e in exposures)
        
        for limit in self.exposure_limits:
            # Filtrer les expositions pour cette limite
            filtered = [
                e for e in exposures
                if e.type == limit.type and (limit.asset == '*' or e.asset == limit.asset)
            ]
            
            value = sum(e.value for e in filtered)
            percentage = value / total_value if total_value > 0 else 0
            
            # Vérifier les limites
            if limit.max_value and value > limit.max_value:
                self._trigger_alert(
                    f"Exposure limit exceeded: {limit.type.value} = {value:.2f} > {limit.max_value:.2f}",
                    limit.severity
                )
            
            if limit.max_percentage and percentage > limit.max_percentage:
                self._trigger_alert(
                    f"Exposure percentage limit exceeded: {limit.type.value} = {percentage:.1%} > {limit.max_percentage:.1%}",
                    limit.severity
                )
    
    def _trigger_alert(self, message: str, severity: str = "warning"):
        """
        Déclenche une alerte
        
        Args:
            message: Message d'alerte
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
        
        logger.warning(f"[EXPOSURE LIMIT] {message}")
    
    # ============================================================
    # HEDGING MANAGEMENT
    # ============================================================
    
    def add_hedging_position(self, position: HedgingPosition):
        """
        Ajoute une position de couverture
        
        Args:
            position: Position de couverture
        """
        with self._lock:
            self.hedging_positions[position.id] = position
            self.stats['hedging_positions'] = len(self.hedging_positions)
            self._update_stats()
    
    def remove_hedging_position(self, position_id: str):
        """
        Supprime une position de couverture
        
        Args:
            position_id: ID de la position
        """
        with self._lock:
            if position_id in self.hedging_positions:
                del self.hedging_positions[position_id]
                self.stats['hedging_positions'] = len(self.hedging_positions)
                self._update_stats()
    
    def get_hedging_positions(self) -> List[HedgingPosition]:
        """
        Récupère les positions de couverture
        
        Returns:
            List[HedgingPosition]: Positions de couverture
        """
        return list(self.hedging_positions.values())
    
    def calculate_hedge_ratio(self, asset: str) -> float:
        """
        Calcule le ratio de couverture
        
        Args:
            asset: Actif
            
        Returns:
            float: Ratio de couverture
        """
        exposures = self.get_exposures(asset, ExposureType.DELTA)
        total_delta = sum(e.delta or 0 for e in exposures)
        
        hedging_positions = [
            p for p in self.hedging_positions.values()
            if p.asset == asset
        ]
        total_hedge_delta = sum(p.delta for p in hedging_positions)
        
        if total_delta == 0:
            return 1.0
        
        hedge_ratio = abs(total_hedge_delta / total_delta)
        return min(hedge_ratio, 1.0)
    
    def calculate_hedge_effectiveness(self) -> float:
        """
        Calcule l'efficacité de la couverture
        
        Returns:
            float: Efficacité de la couverture
        """
        with self._lock:
            total_exposure = self.stats['total_exposure']
            hedged_exposure = self.stats['hedged_exposure']
            
            if total_exposure == 0:
                return 1.0
            
            return hedged_exposure / total_exposure
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        exposures = self.get_exposures()
        
        total_exposure = sum(e.value for e in exposures)
        hedged_exposure = sum(
            e.value for e in exposures
            if e.metadata.get('hedged', False)
        )
        
        self.stats['total_exposure'] = total_exposure
        self.stats['hedged_exposure'] = hedged_exposure
        self.stats['unhedged_exposure'] = total_exposure - hedged_exposure
        self.stats['hedge_ratio'] = hedged_exposure / total_exposure if total_exposure > 0 else 0
        self.stats['exposure_by_type'] = self.get_exposure_by_type()
        self.stats['exposure_by_asset'] = self.get_exposure_by_asset()
        self.stats['hedge_effectiveness'] = self.calculate_hedge_effectiveness()
    
    # ============================================================
    # OPTIMAL HEDGING
    # ============================================================
    
    def calculate_optimal_hedge(self, asset: str) -> Dict[str, Any]:
        """
        Calcule la couverture optimale
        
        Args:
            asset: Actif
            
        Returns:
            Dict[str, Any]: Couverture optimale
        """
        exposures = self.get_exposures(asset, ExposureType.DELTA)
        
        if not exposures:
            return {
                'asset': asset,
                'optimal_hedge': 0,
                'hedge_ratio': 1.0,
                'confidence': 0,
            }
        
        # Calculer le delta total
        total_delta = sum(e.delta or 0 for e in exposures)
        
        # Optimisation (simplifiée)
        optimal_hedge = -total_delta * 0.5  # Couverture à 50%
        
        return {
            'asset': asset,
            'optimal_hedge': optimal_hedge,
            'hedge_ratio': 0.5,
            'confidence': 0.8,
            'current_delta': total_delta,
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
        
        logger.info("ExposureManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("ExposureManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self.update()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def update(self):
        """Met à jour les données"""
        with self._lock:
            self._update_stats()
            
            # Sauvegarder l'historique
            snapshot = {
                'timestamp': time.time(),
                'stats': self.stats.copy(),
                'exposure_breakdown': self.get_exposure_breakdown(),
            }
            self.history.append(snapshot)
            
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport d'exposition
        
        Returns:
            Dict[str, Any]: Rapport
        """
        return {
            'timestamp': time.time(),
            'summary': {
                'total_exposure': self.stats['total_exposure'],
                'hedged_exposure': self.stats['hedged_exposure'],
                'unhedged_exposure': self.stats['unhedged_exposure'],
                'hedge_ratio': self.stats['hedge_ratio'],
                'hedge_effectiveness': self.stats['hedge_effectiveness'],
            },
            'by_type': self.get_exposure_by_type(),
            'by_asset': self.get_exposure_by_asset(),
            'hedging_positions': len(self.hedging_positions),
            'limits': [
                {
                    'type': l.type.value,
                    'asset': l.asset,
                    'max_value': l.max_value,
                    'max_percentage': l.max_percentage,
                    'severity': l.severity,
                }
                for l in self.exposure_limits
            ],
            'alerts': self.alerts[-10:],
            'history': self.history[-10:],
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return self.stats.copy()

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_exposure_manager: Optional[ExposureManager] = None

def get_exposure_manager(
    config: Optional[Dict[str, Any]] = None
) -> ExposureManager:
    """
    Récupère le gestionnaire d'exposition (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        ExposureManager: Gestionnaire d'exposition
    """
    global _exposure_manager
    if _exposure_manager is None:
        _exposure_manager = ExposureManager(config)
    return _exposure_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ExposureType',
    'ExposureDirection',
    'HedgingStrategy',
    'Exposure',
    'ExposureLimit',
    'HedgingPosition',
    'ExposureManager',
    'get_exposure_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Exposure manager module initialized")
