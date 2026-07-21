"""
NEXUS AI TRADING SYSTEM - Hedge Bot Leverage Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de levier pour le bot de couverture
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

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class LeverageType(Enum):
    """Types de levier"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    VOLATILITY = "volatility"
    KELLY = "kelly"
    OPTIMAL = "optimal"
    MARGIN = "margin"
    CUSTOM = "custom"

class LeverageMode(Enum):
    """Modes de levier"""
    LONG = "long"
    SHORT = "short"
    ISOLATED = "isolated"
    CROSS = "cross"
    HEDGED = "hedged"

class LeverageStatus(Enum):
    """Statuts de levier"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    LIQUIDATED = "liquidated"
    CLOSED = "closed"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class LeveragePosition:
    """Position avec levier"""
    id: str
    symbol: str
    size: float
    leverage: float
    mode: LeverageMode
    entry_price: float
    current_price: float
    liquidation_price: float
    margin_used: float
    margin_available: float
    status: LeverageStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LeverageMetrics:
    """Métriques de levier"""
    total_leverage: float
    average_leverage: float
    max_leverage: float
    min_leverage: float
    margin_usage: float
    liquidation_risk: float
    pnl: float
    roe: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LeverageConfig:
    """Configuration de levier"""
    enabled: bool = True
    default_leverage: float = 1.0
    max_leverage: float = 10.0
    min_leverage: float = 1.0
    margin_requirement: float = 0.10  # 10%
    maintenance_margin: float = 0.05   # 5%
    liquidation_threshold: float = 0.80
    auto_adjust: bool = True
    volatility_factor: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# LEVERAGE MANAGER
# ============================================================

class LeverageManager:
    """
    Gestionnaire de levier pour le bot de couverture
    
    Gère les positions avec levier et les risques associés
    """
    
    def __init__(
        self,
        config: Optional[LeverageConfig] = None,
        update_interval: int = 10,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de levier
        
        Args:
            config: Configuration de levier
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or LeverageConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Positions
        self.positions: Dict[str, LeveragePosition] = {}
        self.active_positions: Dict[str, LeveragePosition] = {}
        self.closed_positions: Dict[str, LeveragePosition] = {}
        
        # Métriques
        self.metrics: Optional[LeverageMetrics] = None
        
        # Statistiques
        self.stats = {
            'total_positions': 0,
            'active_positions': 0,
            'closed_positions': 0,
            'liquidated_positions': 0,
            'total_leverage': 0.0,
            'avg_leverage': 0.0,
            'max_leverage': 0.0,
            'margin_usage': 0.0,
            'total_pnl': 0.0,
            'roe': 0.0,
        }
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'position_opened': [],
            'position_updated': [],
            'position_closed': [],
            'margin_call': [],
            'liquidation': [],
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Capital
        self.capital: float = 10000.0
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("LeverageManager initialized")
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def open_position(
        self,
        symbol: str,
        size: float,
        leverage: Optional[float] = None,
        mode: LeverageMode = LeverageMode.CROSS,
        entry_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LeveragePosition:
        """
        Ouvre une position avec levier
        
        Args:
            symbol: Symbole
            size: Taille de la position
            leverage: Levier à utiliser
            mode: Mode de levier
            entry_price: Prix d'entrée
            metadata: Métadonnées
            
        Returns:
            LeveragePosition: Position ouverte
        """
        with self._lock:
            # Calculer le levier
            if leverage is None:
                leverage = self._calculate_optimal_leverage(symbol)
            
            # Limiter le levier
            leverage = min(leverage, self.config.max_leverage)
            leverage = max(leverage, self.config.min_leverage)
            
            # Calculer la marge
            margin_used = size * self.config.margin_requirement
            margin_available = self.capital * (1 - self.config.margin_requirement)
            
            # Prix d'entrée
            if entry_price is None:
                entry_price = 1.0  # Simulé
            
            # Prix de liquidation
            liquidation_price = self._calculate_liquidation_price(
                entry_price=entry_price,
                leverage=leverage,
                mode=mode,
                size=size
            )
            
            position = LeveragePosition(
                id=f"lev_{int(time.time())}_{symbol}",
                symbol=symbol,
                size=size,
                leverage=leverage,
                mode=mode,
                entry_price=entry_price,
                current_price=entry_price,
                liquidation_price=liquidation_price,
                margin_used=margin_used,
                margin_available=margin_available,
                status=LeverageStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata=metadata or {}
            )
            
            self.positions[position.id] = position
            self.active_positions[position.id] = position
            self.stats['total_positions'] += 1
            self.stats['active_positions'] += 1
            
            self._update_stats()
            self._trigger_event('position_opened', position)
            
            logger.info(f"Leverage position opened: {symbol} - {leverage:.1f}x")
            return position
    
    def _calculate_optimal_leverage(self, symbol: str) -> float:
        """
        Calcule le levier optimal
        
        Args:
            symbol: Symbole
            
        Returns:
            float: Levier optimal
        """
        # Simuler le calcul du levier optimal
        # À implémenter avec des données réelles
        base_leverage = self.config.default_leverage
        
        # Ajustement de volatilité
        volatility = self._get_volatility(symbol)
        volatility_factor = 1 / (1 + volatility * self.config.volatility_factor)
        
        optimal_leverage = base_leverage * volatility_factor
        
        return min(optimal_leverage, self.config.max_leverage)
    
    def _get_volatility(self, symbol: str) -> float:
        """
        Récupère la volatilité d'un symbole
        
        Args:
            symbol: Symbole
            
        Returns:
            float: Volatilité
        """
        # Simulation de volatilité
        # À implémenter avec des données réelles
        return 0.02  # 2% par défaut
    
    def _calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        mode: LeverageMode,
        size: float
    ) -> float:
        """
        Calcule le prix de liquidation
        
        Args:
            entry_price: Prix d'entrée
            leverage: Levier
            mode: Mode de levier
            size: Taille
            
        Returns:
            float: Prix de liquidation
        """
        # Calcul simplifié du prix de liquidation
        if mode == LeverageMode.LONG:
            liquidation_price = entry_price * (1 - 1 / leverage)
        elif mode == LeverageMode.SHORT:
            liquidation_price = entry_price * (1 + 1 / leverage)
        else:
            liquidation_price = entry_price * (1 - 1 / leverage * 0.5)
        
        return liquidation_price
    
    def update_position(self, position_id: str, current_price: float) -> bool:
        """
        Met à jour une position
        
        Args:
            position_id: ID de la position
            current_price: Prix actuel
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            if position.status != LeverageStatus.ACTIVE:
                return False
            
            position.current_price = current_price
            position.updated_at = datetime.now()
            
            # Vérifier la liquidation
            if self._check_liquidation(position):
                self._liquidate_position(position_id)
                return True
            
            # Vérifier l'appel de marge
            margin_usage = position.margin_used / self.capital
            if margin_usage > self.config.liquidation_threshold:
                self._trigger_event('margin_call', position)
                self._add_alert(
                    f"Margin call: {position.symbol} - {margin_usage:.1%} margin used",
                    "warning"
                )
            
            # Ajuster automatiquement le levier
            if self.config.auto_adjust:
                self._adjust_leverage(position)
            
            self._trigger_event('position_updated', position)
            return True
    
    def _check_liquidation(self, position: LeveragePosition) -> bool:
        """
        Vérifie si la position doit être liquidée
        
        Args:
            position: Position à vérifier
            
        Returns:
            bool: True si liquidation
        """
        if position.mode == LeverageMode.LONG:
            if position.current_price <= position.liquidation_price:
                return True
        elif position.mode == LeverageMode.SHORT:
            if position.current_price >= position.liquidation_price:
                return True
        
        return False
    
    def _liquidate_position(self, position_id: str) -> bool:
        """
        Liquide une position
        
        Args:
            position_id: ID de la position
            
        Returns:
            bool: True si liquidée
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            position.status = LeverageStatus.LIQUIDATED
            position.updated_at = datetime.now()
            
            self.active_positions.pop(position_id, None)
            self.closed_positions[position_id] = position
            self.stats['active_positions'] -= 1
            self.stats['closed_positions'] += 1
            self.stats['liquidated_positions'] += 1
            
            self._update_stats()
            self._trigger_event('liquidation', position)
            
            self._add_alert(
                f"Position liquidated: {position.symbol} @ {position.current_price:.2f}",
                "critical"
            )
            
            logger.warning(f"Position liquidated: {position_id}")
            return True
    
    def _adjust_leverage(self, position: LeveragePosition):
        """
        Ajuste le levier automatiquement
        
        Args:
            position: Position à ajuster
        """
        # Simuler l'ajustement du levier
        volatility = self._get_volatility(position.symbol)
        target_leverage = self.config.default_leverage / (1 + volatility * 2)
        
        if abs(position.leverage - target_leverage) > 0.5:
            position.leverage = target_leverage
            logger.debug(f"Leverage adjusted: {position.symbol} -> {target_leverage:.1f}x")
    
    def close_position(self, position_id: str) -> bool:
        """
        Ferme une position
        
        Args:
            position_id: ID de la position
            
        Returns:
            bool: True si fermée
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            position.status = LeverageStatus.CLOSED
            position.updated_at = datetime.now()
            
            # Calculer le P&L
            if position.mode == LeverageMode.LONG:
                pnl = (position.current_price - position.entry_price) * position.size
            else:
                pnl = (position.entry_price - position.current_price) * position.size
            
            position.metadata['pnl'] = pnl
            
            self.active_positions.pop(position_id, None)
            self.closed_positions[position_id] = position
            self.stats['active_positions'] -= 1
            self.stats['closed_positions'] += 1
            
            self._update_stats()
            self._trigger_event('position_closed', position)
            
            logger.info(f"Position closed: {position_id} - PNL: {pnl:.2f}")
            return True
    
    def get_position(self, position_id: str) -> Optional[LeveragePosition]:
        """
        Récupère une position
        
        Args:
            position_id: ID de la position
            
        Returns:
            Optional[LeveragePosition]: Position
        """
        return self.positions.get(position_id)
    
    def get_active_positions(self) -> List[LeveragePosition]:
        """
        Récupère les positions actives
        
        Returns:
            List[LeveragePosition]: Positions actives
        """
        return list(self.active_positions.values())
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def calculate_metrics(self) -> LeverageMetrics:
        """
        Calcule les métriques de levier
        
        Returns:
            LeverageMetrics: Métriques calculées
        """
        with self._lock:
            active = list(self.active_positions.values())
            if not active:
                return LeverageMetrics(0,0,0,0,0,0,0,0)
            
            total_leverage = sum(p.leverage for p in active)
            avg_leverage = total_leverage / len(active) if active else 0
            max_leverage = max(p.leverage for p in active) if active else 0
            min_leverage = min(p.leverage for p in active) if active else 0
            
            total_margin = sum(p.margin_used for p in active)
            margin_usage = total_margin / self.capital if self.capital > 0 else 0
            
            # Risque de liquidation
            liquidation_risk = sum(
                1 / (1 + abs(p.current_price - p.liquidation_price) / p.current_price)
                for p in active
            ) / len(active) if active else 0
            
            # P&L et ROE
            total_pnl = sum(
                (p.current_price - p.entry_price) * p.size if p.mode == LeverageMode.LONG
                else (p.entry_price - p.current_price) * p.size
                for p in active
            )
            roe = total_pnl / self.capital if self.capital > 0 else 0
            
            metrics = LeverageMetrics(
                total_leverage=total_leverage,
                average_leverage=avg_leverage,
                max_leverage=max_leverage,
                min_leverage=min_leverage,
                margin_usage=margin_usage,
                liquidation_risk=liquidation_risk,
                pnl=total_pnl,
                roe=roe
            )
            
            self.metrics = metrics
            return metrics
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        metrics = self.calculate_metrics()
        self.stats.update({
            'total_leverage': metrics.total_leverage,
            'avg_leverage': metrics.average_leverage,
            'max_leverage': metrics.max_leverage,
            'margin_usage': metrics.margin_usage,
            'total_pnl': metrics.pnl,
            'roe': metrics.roe,
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
                'total_leverage': metrics.total_leverage,
                'avg_leverage': metrics.average_leverage,
                'max_leverage': metrics.max_leverage,
                'min_leverage': metrics.min_leverage,
                'margin_usage': metrics.margin_usage,
                'liquidation_risk': metrics.liquidation_risk,
                'pnl': metrics.pnl,
                'roe': metrics.roe,
            },
            'active_positions': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'size': p.size,
                    'leverage': p.leverage,
                    'mode': p.mode.value,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'liquidation_price': p.liquidation_price,
                    'margin_used': p.margin_used,
                    'margin_available': p.margin_available,
                }
                for p in self.active_positions.values()
            ],
            'alerts': self.alerts[-10:],
        }
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un callback
        
        Args:
            event: Événement
            callback: Fonction de callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_event(self, event: str, data: Any):
        """
        Déclenche un événement
        
        Args:
            event: Événement
            data: Données
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ============================================================
    # ALERTS
    # ============================================================
    
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
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._update_task = threading.Thread(target=self._update_loop, daemon=True)
        self._update_task.start()
        
        logger.info("LeverageManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("LeverageManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_positions()
                self._check_margin_calls()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_positions(self):
        """Met à jour les positions"""
        # À implémenter avec les prix réels
        pass
    
    def _check_margin_calls(self):
        """Vérifie les appels de marge"""
        for position in self.active_positions.values():
            margin_usage = position.margin_used / self.capital
            if margin_usage > self.config.liquidation_threshold * 0.8:
                self._add_alert(
                    f"Margin warning: {position.symbol} - {margin_usage:.1%} margin used",
                    "warning"
                )

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_leverage_manager: Optional[LeverageManager] = None

def get_leverage_manager(
    config: Optional[LeverageConfig] = None
) -> LeverageManager:
    """
    Récupère le gestionnaire de levier (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        LeverageManager: Gestionnaire de levier
    """
    global _leverage_manager
    if _leverage_manager is None:
        _leverage_manager = LeverageManager(config)
    return _leverage_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'LeverageType',
    'LeverageMode',
    'LeverageStatus',
    'LeveragePosition',
    'LeverageMetrics',
    'LeverageConfig',
    'LeverageManager',
    'get_leverage_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Leverage manager module initialized")
